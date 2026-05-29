const mongoose = require('mongoose');

const watch_next_schema = new mongoose.Schema({
    related_id: String,
    slug: String,
    title: String,
    duration: String,
    viewedCount: String,
    presenterDisplayName: String
}, { _id: false });

const talk_schema = new mongoose.Schema({
    _id: String,
    slug: String,
    speakers: String,
    title: String,
    url: String,
    description: String,
    duration: String,
    publishedAt: String,
    tags: [String],
    watch_next: [watch_next_schema],
    comprehend_analysis: mongoose.Schema.Types.Mixed
}, { collection: 'tedx_data' });

module.exports = mongoose.model('talk', talk_schema);