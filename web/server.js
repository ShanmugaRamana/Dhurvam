require('dotenv').config();
const express = require('express');
const path = require('path');
const app = express();
const port = 3000;

// Import Routes
const pageRoutes = require('./routes/pages');
const authRoutes = require('./routes/auth');
const apiRoutes = require('./routes/api');

// Middleware to parse JSON bodies
app.use(express.json());

// Set view engine
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

// Static files
app.use(express.static(path.join(__dirname, 'public')));

// Use Routes
app.use('/', pageRoutes);
app.use('/api', authRoutes);
app.use('/api', apiRoutes);

// Start server
app.listen(port, () => {
    console.log(`Server running at http://localhost:${port}`);
});
