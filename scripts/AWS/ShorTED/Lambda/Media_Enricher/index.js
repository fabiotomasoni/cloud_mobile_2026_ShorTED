const fs = require('fs');
const path = require('path');
const { S3Client, GetObjectCommand, PutObjectCommand } = require('@aws-sdk/client-s3');
const { extractTedMedia } = require('./media_extractor');

const s3 = new S3Client({});
const MEDIA_EXTRACTION_VERSION = process.env.MEDIA_EXTRACTION_VERSION || 'ted-media-enricher-v1';

function loadEnv() {
    const envPath = path.join(__dirname, '.env');
    if (!fs.existsSync(envPath)) return;

    const envFile = fs.readFileSync(envPath, 'utf8');
    envFile.split(/\r?\n/).forEach(line => {
        if (!line || line.trim().startsWith('#')) return;
        const [key, ...valueParts] = line.split('=');
        if (key && valueParts.length > 0) {
            process.env[key.trim()] = valueParts.join('=').trim();
        }
    });
}

loadEnv();

function streamToString(stream) {
    return new Promise((resolve, reject) => {
        const chunks = [];
        stream.on('data', chunk => chunks.push(chunk));
        stream.on('error', reject);
        stream.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')));
    });
}

function destinationKey(sourceKey) {
    const enrichedPrefix = process.env.ENRICHED_PREFIX || '';
    const processedPrefix = process.env.PROCESSED_PREFIX || '';
    let key = sourceKey;

    if (processedPrefix && key.startsWith(processedPrefix)) {
        key = key.slice(processedPrefix.length).replace(/^\/+/, '');
    }

    if (!enrichedPrefix) return key;
    return `${enrichedPrefix.replace(/\/+$/, '')}/${key}`;
}

function buildTalkUrl(data) {
    if (data.url) return data.url;
    if (data.slug) return `https://www.ted.com/talks/${data.slug}`;
    return '';
}

async function readJsonFromS3(bucket, key) {
    const response = await s3.send(new GetObjectCommand({ Bucket: bucket, Key: key }));
    const raw = await streamToString(response.Body);
    return JSON.parse(raw);
}

async function writeJsonToS3(bucket, key, data) {
    await s3.send(new PutObjectCommand({
        Bucket: bucket,
        Key: key,
        Body: JSON.stringify(data, null, 2),
        ContentType: 'application/json; charset=utf-8',
    }));
}

async function enrichTalk(data) {
    const now = new Date().toISOString();
    const talkUrl = buildTalkUrl(data);

    try {
        const media = await extractTedMedia({
            slug: data.slug,
            talkUrl,
        });

        return {
            ...data,
            ...media,
            mediaExtractedAt: now,
            mediaExtractionVersion: MEDIA_EXTRACTION_VERSION,
            mediaExtractionStatus: 'completed',
        };
    } catch (error) {
        return {
            ...data,
            embedUrl: data.slug ? `https://embed.ted.com/talks/${encodeURIComponent(data.slug)}` : '',
            thumbnailUrl: data.thumbnailUrl || data.imageUrl || data.image || '',
            thumbnailUrlHd: data.thumbnailUrlHd || '',
            thumbnailUrlFullHd: data.thumbnailUrlFullHd || '',
            hlsUrl: data.hlsUrl || '',
            mp4Url: data.mp4Url || '',
            mediaExtractedAt: now,
            mediaExtractionVersion: MEDIA_EXTRACTION_VERSION,
            mediaExtractionStatus: 'failed',
            mediaExtractionError: error.message,
        };
    }
}

function recordsFromEvent(event) {
    if (event && Array.isArray(event.Records)) {
        return event.Records.map(record => {
            if (record.s3) {
                return {
                    bucket: record.s3.bucket.name,
                    key: decodeURIComponent(record.s3.object.key.replace(/\+/g, ' ')),
                };
            }

            const body = typeof record.body === 'string' ? JSON.parse(record.body) : record.body;
            return { bucket: body.bucket, key: body.file_key || body.key };
        });
    }

    if (event && event.bucket && (event.file_key || event.key)) {
        return [{ bucket: event.bucket, key: event.file_key || event.key }];
    }

    throw new Error('event must contain S3 records, SQS records, or bucket/file_key');
}

exports.handler = async (event) => {
    const outputBucket = process.env.ENRICHED_BUCKET_NAME;
    if (!outputBucket) {
        return { statusCode: 500, body: 'ENRICHED_BUCKET_NAME is required' };
    }

    const records = recordsFromEvent(event);
    const results = [];

    for (const record of records) {
        const data = await readJsonFromS3(record.bucket, record.key);
        const enriched = await enrichTalk(data);
        const outKey = destinationKey(record.key);
        await writeJsonToS3(outputBucket, outKey, enriched);
        results.push({ source: `s3://${record.bucket}/${record.key}`, destination: `s3://${outputBucket}/${outKey}`, status: enriched.mediaExtractionStatus });
    }

    return { statusCode: 200, body: JSON.stringify({ processed: results.length, results }) };
};

module.exports.enrichTalk = enrichTalk;
module.exports.destinationKey = destinationKey;
