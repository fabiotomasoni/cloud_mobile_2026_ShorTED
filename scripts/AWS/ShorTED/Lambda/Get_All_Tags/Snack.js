const mongoose = require('mongoose');

const snack_schema = new mongoose.Schema({
    _id: String,
    speaker: String,
    talkTitle: String,
    topic: String,
    quote: String,
    motivationalText: String,
    aphorism: String,
    tags: [String],
    endTime: Number,
    talkUrl: String
}, { collection: 'snacks' });

module.exports = mongoose.model('snack', snack_schema);
