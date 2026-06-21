const mongoose = require('mongoose');

const snack_schema = new mongoose.Schema({
    _id: String,
    segmentId: String,
    talkId: String,
    talkSlug: String,
    speaker: String,
    talkTitle: String,
    topic: String,
    quote: String,
    motivationalText: String,
    aphorism: String,
    tags: [String],
    score: Number,
    startTime: Number,
    endTime: Number,
    talkUrl: String,
    language: String,
    aiPipelineVersion: String,
    sourceHash: String,
    createdAt: mongoose.Schema.Types.Mixed
}, { collection: 'snacks' });

module.exports = mongoose.model('snack', snack_schema);
