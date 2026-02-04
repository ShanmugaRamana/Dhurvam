const express = require('express');
const router = express.Router();

router.get('/', (req, res) => {
    res.set('Cache-Control', 'no-store, no-cache, must-revalidate, private');
    res.render('login');
});

router.get('/home', (req, res) => {
    res.set('Cache-Control', 'no-store, no-cache, must-revalidate, private');
    // In a real app, check session/cookie here
    res.render('home');
});

module.exports = router;
