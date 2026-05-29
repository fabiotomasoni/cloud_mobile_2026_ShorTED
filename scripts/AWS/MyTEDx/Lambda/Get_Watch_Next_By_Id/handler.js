const connect_to_db = require('./db');
const talk = require('./Talks');

module.exports.handler = async (event, context, callback) => {
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
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                message: 'Invalid JSON body.'
            })
        });
    }

    const queryParams = event.queryStringParameters || {};

    const id = body.id || queryParams.id;

    const doc_per_page = parseInt(
        body.doc_per_page || queryParams.doc_per_page || 10,
        10
    );

    const page = parseInt(
        body.page || queryParams.page || 1,
        10
    );

    console.log('Parsed params:', {
        id,
        doc_per_page,
        page
    });

    if (!id) {
        return callback(null, {
            statusCode: 400,
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                message: 'Could not fetch watch next videos. Talk id is required.'
            })
        });
    }

    if (doc_per_page <= 0 || page <= 0 || isNaN(doc_per_page) || isNaN(page)) {
        return callback(null, {
            statusCode: 400,
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                message: 'doc_per_page and page must be valid numbers greater than 0.'
            })
        });
    }

    try {
        await connect_to_db();

        console.log(`=> get watch_next for talk id: ${id}`);

        const selectedTalk = await talk.findOne({ _id: id }).select({
            _id: 1,
            slug: 1,
            title: 1,
            watch_next: 1
        });

        console.log('Mongo selectedTalk found:', !!selectedTalk);

        if (!selectedTalk) {
            return callback(null, {
                statusCode: 404,
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    message: 'Talk not found.'
                })
            });
        }

        const watchNext = selectedTalk.watch_next || [];

        const startIndex = (page - 1) * doc_per_page;
        const endIndex = startIndex + doc_per_page;

        const paginatedWatchNext = watchNext.slice(startIndex, endIndex);

        return callback(null, {
            statusCode: 200,
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                talk: {
                    id: selectedTalk._id,
                    slug: selectedTalk.slug,
                    title: selectedTalk.title
                },
                related_videos: paginatedWatchNext
            })
        });

    } catch (err) {
        console.error('Error fetching watch next videos:', err);

        return callback(null, {
            statusCode: err.statusCode || 500,
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                message: 'Could not fetch watch next videos.',
                error: err.message
            })
        });
    }
};