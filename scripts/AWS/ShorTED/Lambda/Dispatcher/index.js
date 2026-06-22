const fs = require('fs');
const { S3Client, ListObjectsV2Command } = require("@aws-sdk/client-s3");
const { SQSClient, SendMessageBatchCommand } = require("@aws-sdk/client-sqs");

// 1. Lettura del file .env
const loadEnv = () => {
    try {
        const envFile = fs.readFileSync('./.env', 'utf8');
        envFile.split(/\r?\n/).forEach(line => {
            if (!line || line.startsWith('#')) return;
            const [key, ...valueParts] = line.split('=');
            if (key && valueParts.length > 0) {
                process.env[key.trim()] = valueParts.join('=').trim();
            }
        });
        console.log("File .env caricato.");
    } catch (error) {
        console.warn("Nessun file .env trovato.");
    }
};

loadEnv();
const s3 = new S3Client({});
const sqs = new SQSClient({});

// Funzione helper per dividere un array in blocchi da N elementi
const chunkArray = (array, chunkSize) => {
    const chunks = [];
    for (let i = 0; i < array.length; i += chunkSize) {
        chunks.push(array.slice(i, i + chunkSize));
    }
    return chunks;
};

exports.handler = async (event) => {
    console.log("Lambda Dispatcher Definitiva (Paginazione + Batch)!");

    const bucketName = process.env.ENRICHED_BUCKET_NAME || process.env.PROCESSED_BUCKET_NAME;
    const prefix = process.env.ENRICHED_PREFIX || process.env.PROCESSED_PREFIX || undefined;
    const language = process.env.DEFAULT_LANGUAGE || undefined;
    const queueUrl = process.env.SQS_QUEUE_URL;

    if (!bucketName || !queueUrl) {
        return { statusCode: 500, body: "Errore: variabili d'ambiente mancanti" };
    }

    try {
        // 2. Leggi TUTTI i file dal bucket S3 (Paginazione)
        let isTruncated = true;
        let continuationToken = undefined;
        const filesToProcess = [];

        console.log(`Inizio lettura dal bucket ${bucketName}${prefix ? ` con prefisso ${prefix}` : ''}...`);

        while (isTruncated) {
            const listCommand = new ListObjectsV2Command({
                Bucket: bucketName,
                Prefix: prefix,
                ContinuationToken: continuationToken
            });
            const s3Response = await s3.send(listCommand);

            if (s3Response.Contents) {
                const keys = s3Response.Contents
                    .map(item => item.Key)
                    .filter(key => key.endsWith('.json'));
                filesToProcess.push(...keys); // Aggiunge i nuovi file all'array totale
            }

            isTruncated = s3Response.IsTruncated;
            continuationToken = s3Response.NextContinuationToken;
        }
            
        console.log(`Lettura completata. Trovati in totale ${filesToProcess.length} file JSON.`);

        if (filesToProcess.length === 0) {
            return { statusCode: 200, body: "Nessun file trovato nel bucket." };
        }

        // 3. Dividi tutti i file in pacchi da 10
        const batches = chunkArray(filesToProcess, 10);
        let successCount = 0;
        let errorCount = 0;

        // 4. Invia i pacchi a SQS
        const sqsPromises = batches.map(async (batch, batchIndex) => {
            const entries = batch.map((key, index) => ({
                Id: `msg_${batchIndex}_${index}`,
                MessageBody: JSON.stringify({ bucket: bucketName, file_key: key, ...(language ? { language } : {}) })
            }));

            const batchCommand = new SendMessageBatchCommand({
                QueueUrl: queueUrl,
                Entries: entries
            });

            try {
                const response = await sqs.send(batchCommand);
                if (response.Successful) successCount += response.Successful.length;
                if (response.Failed) errorCount += response.Failed.length;
            } catch (err) {
                console.error(`Errore invio batch ${batchIndex}:`, err);
                errorCount += batch.length;
            }
        });

        // Aspettiamo che tutti i pacchi siano stati inviati
        await Promise.all(sqsPromises);

        const resultStr = `Operazione completata! Messaggi inviati: ${successCount}. Errori: ${errorCount}.`;
        console.log(resultStr);

        return {
            statusCode: 200,
            body: JSON.stringify({ message: resultStr })
        };

    } catch (error) {
        console.error("Errore fatale:", error);
        return {
            statusCode: 500,
            body: JSON.stringify({ error: "Errore interno durante l'elaborazione" })
        };
    }
};
