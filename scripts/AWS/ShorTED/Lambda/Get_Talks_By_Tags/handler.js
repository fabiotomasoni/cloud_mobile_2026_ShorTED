const connect_to_db = require('./db');
const snack = require('./Snack');

module.exports.get_by_tags = async (event, context, callback) => {
    context.callbackWaitsForEmptyEventLoop = false;
    console.log('Received event:', JSON.stringify(event, null, 2));

    let body = {};
    try {
        if (event.body) {
            body = typeof event.body === 'string'
                ? JSON.parse(event.body)
                : event.body;
        } else {
            body = event || {};
        }
    } catch (err) {
        console.error('Invalid JSON body:', err);
        return callback(null, {
            statusCode: 400,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: 'Invalid JSON body.' })
        });
    }

    const queryParams = event.queryStringParameters || {};
    const tagsInput = body.tags || queryParams.tags;

    let tags = [];
    if (tagsInput) {
        if (Array.isArray(tagsInput)) {
            tags = tagsInput;
        } else if (typeof tagsInput === 'string') {
            tags = tagsInput.split(',').map(t => t.trim()).filter(Boolean);
        }
    }

    if (tags.length === 0) {
        return callback(null, {
            statusCode: 400,
            headers: { 'Content-Type': 'text/plain' },
            body: 'Could not fetch the talks. Tags parameter is missing or empty.'
        });
    }

    const doc_per_page = parseInt(
        body.doc_per_page || queryParams.doc_per_page || 10,
        10
    );
    const page = parseInt(
        body.page || queryParams.page || 1,
        10
    );

    if (doc_per_page <= 0 || page <= 0 || isNaN(doc_per_page) || isNaN(page)) {
        return callback(null, {
            statusCode: 400,
            headers: { 'Content-Type': 'text/plain' },
            body: 'doc_per_page and page must be valid numbers greater than 0.'
        });
    }

    try {
        await connect_to_db();
        console.log(`=> get_all talks by tags: ${JSON.stringify(tags)}`);

        // Query snacks containing any of the requested tags and project the specific fields
        const matchedSnacks = await snack.find({ tags: { $in: tags } })
            .select('speaker talkTitle topic quote motivationalText aphorism tags endTime talkUrl')
            .skip((doc_per_page * page) - doc_per_page)
            .limit(doc_per_page);

        return callback(null, {
            statusCode: 200,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(matchedSnacks)
        });

    } catch (err) {
        console.error('Error fetching talks by tags:', err);
        return callback(null, {
            statusCode: err.statusCode || 500,
            headers: { 'Content-Type': 'text/plain' },
            body: 'Could not fetch the talks.'
        });
    }
};
