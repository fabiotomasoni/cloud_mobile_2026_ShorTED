// CONNECTION TO DB

const mongoose = require('mongoose');
mongoose.Promise = global.Promise;
let isConnected;

require('dotenv').config({ path: './variables.env' });

module.exports = connect_to_db = () => {
    if (isConnected) {
        console.log('=> using existing database connection');
        return Promise.resolve();
    }
 
    console.log('=> using new database connection');
    const dbName = process.env.DB_NAME || 'unibg_tedx_2026';
    return mongoose.connect(process.env.DB, { dbName, useNewUrlParser: true, useUnifiedTopology: true }).then(db => {
        isConnected = db.connections[0].readyState;
    });
};
