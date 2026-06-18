const connect_to_db = require('./db');
const snack = require('./Snack');

module.exports.get_all_tags = async (event, context, callback) => {
    context.callbackWaitsForEmptyEventLoop = false;
    console.log('Received event:', JSON.stringify(event, null, 2));

    try {
        await connect_to_db();
        console.log('=> get_all_tags');

        // Fetch all distinct tags from the snacks collection
        const rawTags = await snack.distinct('tags');

        // Clean up and filter tags (ensure they are non-empty strings)
        const uniqueTags = rawTags
            .filter(t => typeof t === 'string' && t.trim() !== '')
            .map(t => t.trim());

        // Sort alphabetically
        uniqueTags.sort((a, b) => a.localeCompare(b));

        return callback(null, {
            statusCode: 200,
            headers: {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            body: JSON.stringify(uniqueTags)
        });

    } catch (err) {
        console.error('Error fetching unique tags:', err);
        return callback(null, {
            statusCode: err.statusCode || 500,
            headers: { 'Content-Type': 'text/plain' },
            body: 'Could not fetch unique tags.'
        });
    }
};
