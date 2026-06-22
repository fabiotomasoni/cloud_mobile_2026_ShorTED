const assert = require('assert');
const {
    buildMediaFields,
    extractMediaFromNextData,
    extractNextData,
    normaliseThumbnailUrl,
} = require('./media_extractor');

const hls = 'https://hls.ted.com/project_masters/1521/manifest.m3u8?intro_master_id=9294';
const mp4Low = 'https://py.tedcdn.com/products/example-600k.mp4';
const mp4High = 'https://py.tedcdn.com/products/example-1200k.mp4';
const thumb = 'https://pi.tedcdn.com/r/talkstar-assets.s3.amazonaws.com/production/playlists/playlist_1.jpg?quality=89';

const html = `<html><body><script id="__NEXT_DATA__" type="application/json">${JSON.stringify({
    props: {
        pageProps: {
            media: {
                streams: [hls, mp4Low, mp4High],
                images: { primary: thumb },
            }
        }
    }
})}</script></body></html>`;

const data = extractNextData(html);
const media = extractMediaFromNextData(data);

assert.strictEqual(media.hlsUrl, hls);
assert.strictEqual(media.mp4Url, mp4High);
assert.strictEqual(media.thumbnailUrl, thumb);

const nestedMedia = extractMediaFromNextData({
    props: {
        playerData: JSON.stringify({
            resources: {
                hls: { stream: hls.replace('&', '\\u0026') },
                h264: [{ file: mp4High }],
            },
            thumb,
        }),
    },
});

assert.strictEqual(nestedMedia.hlsUrl, hls);
assert.strictEqual(nestedMedia.mp4Url, mp4High);
assert.strictEqual(nestedMedia.thumbnailUrl, thumb);

assert.strictEqual(
    normaliseThumbnailUrl(thumb, 1920, 1080),
    'https://pi.tedcdn.com/r/talkstar-assets.s3.amazonaws.com/production/playlists/playlist_1.jpg?quality=89&w=1920&h=1080'
);

assert.deepStrictEqual(buildMediaFields({ embedUrl: 'https://embed.ted.com/talks/example', thumbnailUrl: thumb, hlsUrl: hls, mp4Url: mp4High }), {
    embedUrl: 'https://embed.ted.com/talks/example',
    thumbnailUrl: thumb,
    thumbnailUrlHd: 'https://pi.tedcdn.com/r/talkstar-assets.s3.amazonaws.com/production/playlists/playlist_1.jpg?quality=89&w=1280&h=720',
    thumbnailUrlFullHd: 'https://pi.tedcdn.com/r/talkstar-assets.s3.amazonaws.com/production/playlists/playlist_1.jpg?quality=89&w=1920&h=1080',
    hlsUrl: hls,
    mp4Url: mp4High,
});

console.log('media_extractor tests passed');
