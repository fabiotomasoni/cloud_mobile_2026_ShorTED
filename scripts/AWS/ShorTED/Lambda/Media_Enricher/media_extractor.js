const https = require('https');

const DEFAULT_TIMEOUT_MS = 10000;

function getText(url, timeoutMs = DEFAULT_TIMEOUT_MS) {
    return new Promise((resolve, reject) => {
        const req = https.get(url, {
            timeout: timeoutMs,
            headers: {
                'User-Agent': 'ShorTED-Media-Enricher/1.0',
                'Accept': 'text/html,application/json;q=0.9,*/*;q=0.8'
            }
        }, (res) => {
            if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
                res.resume();
                const redirected = new URL(res.headers.location, url).toString();
                resolve(getText(redirected, timeoutMs));
                return;
            }

            if (res.statusCode < 200 || res.statusCode >= 300) {
                res.resume();
                reject(new Error(`GET ${url} failed with status ${res.statusCode}`));
                return;
            }

            let data = '';
            res.setEncoding('utf8');
            res.on('data', chunk => { data += chunk; });
            res.on('end', () => resolve(data));
        });

        req.on('timeout', () => {
            req.destroy(new Error(`GET ${url} timed out after ${timeoutMs}ms`));
        });
        req.on('error', reject);
    });
}

function buildEmbedUrl(slug) {
    return `https://embed.ted.com/talks/${encodeURIComponent(slug)}`;
}

function buildOEmbedUrl(talkUrl) {
    return `https://www.ted.com/services/v1/oembed.json?url=${encodeURIComponent(talkUrl)}`;
}

function normaliseThumbnailUrl(url, width, height) {
    if (!url) return '';
    try {
        const parsed = new URL(url);
        parsed.searchParams.set('w', String(width));
        parsed.searchParams.set('h', String(height));
        return parsed.toString();
    } catch (_) {
        return url;
    }
}

function extractNextData(html) {
    const marker = '<script id="__NEXT_DATA__" type="application/json">';
    const start = html.indexOf(marker);
    if (start < 0) {
        throw new Error('__NEXT_DATA__ script not found');
    }

    const jsonStart = start + marker.length;
    const end = html.indexOf('</script>', jsonStart);
    if (end < 0) {
        throw new Error('__NEXT_DATA__ closing script tag not found');
    }

    const rawJson = html.slice(jsonStart, end);
    return JSON.parse(rawJson);
}

function collectStrings(value, output = []) {
    if (typeof value === 'string') {
        output.push(...extractUrlsFromString(value));
        return output;
    }

    if (Array.isArray(value)) {
        for (const item of value) collectStrings(item, output);
        return output;
    }

    if (value && typeof value === 'object') {
        for (const item of Object.values(value)) collectStrings(item, output);
    }

    return output;
}

function extractUrlsFromString(value) {
    const normalised = value.replace(/\\u0026/g, '&');
    if (/^https?:\/\//i.test(normalised)) {
        return [normalised];
    }

    const matches = normalised.match(/https?:\/\/[^\s"'<>\\]+/gi);
    return matches || [];
}

function unique(values) {
    return [...new Set(values.filter(Boolean))];
}

function pickBestMp4(urls) {
    const ranked = [...urls].sort((a, b) => scoreMp4(b) - scoreMp4(a));
    return ranked[0] || '';
}

function scoreMp4(url) {
    const match = url.match(/(?:-|_)(\d{3,5})k\.mp4/i) || url.match(/(\d{3,5})k/i);
    if (match) return Number(match[1]);
    if (/fallback/i.test(url)) return 1200;
    return 0;
}

function pickBestThumbnail(urls) {
    const imageUrls = urls.filter(url => /\.(jpg|jpeg|png|webp)(\?|$)/i.test(url));
    const tedImages = imageUrls.filter(url => /tedcdn|ted\.com/i.test(url));
    return (tedImages[0] || imageUrls[0] || '');
}

function extractMediaFromNextData(nextData) {
    const strings = unique(collectStrings(nextData));
    const hlsUrls = strings.filter(value => /\.m3u8(\?|$)/i.test(value));
    const mp4Urls = strings.filter(value => /\.mp4(\?|$)/i.test(value));
    const thumbnailCandidates = strings.filter(value => /^https?:\/\//i.test(value));

    return {
        hlsUrl: hlsUrls[0] || '',
        mp4Url: pickBestMp4(mp4Urls),
        thumbnailUrl: pickBestThumbnail(thumbnailCandidates),
    };
}

async function fetchOEmbedThumbnail(talkUrl) {
    if (!talkUrl) return '';
    const raw = await getText(buildOEmbedUrl(talkUrl));
    const parsed = JSON.parse(raw);
    return parsed.thumbnail_url || '';
}

async function extractTedMedia({ slug, talkUrl, timeoutMs = DEFAULT_TIMEOUT_MS }) {
    if (!slug) {
        throw new Error('slug is required');
    }

    const embedUrl = buildEmbedUrl(slug);
    let media = { hlsUrl: '', mp4Url: '', thumbnailUrl: '' };

    const html = await getText(embedUrl, timeoutMs);
    const nextData = extractNextData(html);
    media = extractMediaFromNextData(nextData);

    if (!media.thumbnailUrl && talkUrl) {
        media.thumbnailUrl = await fetchOEmbedThumbnail(talkUrl);
    }

    return buildMediaFields({ embedUrl, ...media });
}

function buildMediaFields(media) {
    return {
        embedUrl: media.embedUrl || '',
        thumbnailUrl: media.thumbnailUrl || '',
        thumbnailUrlHd: normaliseThumbnailUrl(media.thumbnailUrl, 1280, 720),
        thumbnailUrlFullHd: normaliseThumbnailUrl(media.thumbnailUrl, 1920, 1080),
        hlsUrl: media.hlsUrl || '',
        mp4Url: media.mp4Url || '',
    };
}

module.exports = {
    buildEmbedUrl,
    buildMediaFields,
    extractMediaFromNextData,
    extractNextData,
    extractTedMedia,
    normaliseThumbnailUrl,
};
