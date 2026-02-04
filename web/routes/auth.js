const express = require('express');
const router = express.Router();


router.post('/login', async (req, res) => {
    const { email, password } = req.body;
    const apiKey = process.env.API_KEY;
    const backendUrl = process.env.BACKEND_URL;

    try {
        const response = await fetch(`${backendUrl}/api/honeypot/login`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'x-api-key': apiKey
            },
            body: JSON.stringify({ email, password })
        });

        const data = await response.json();

        if (response.ok) {
            res.json({ success: true, message: data.message });
        } else {
            res.status(response.status).json({ success: false, message: data.detail || 'Login failed' });
        }
    } catch (error) {
        console.error('Login error:', error);
        res.status(500).json({ success: false, message: 'Internal server error' });
    }
});

module.exports = router;
