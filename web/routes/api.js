const express = require('express');
const router = express.Router();

const BACKEND_URL = process.env.BACKEND_URL || 'http://127.0.0.1:8000';
const API_KEY = process.env.API_KEY;

// Proxy POST /detect to FastAPI
router.post('/detect', async (req, res) => {
    try {
        const response = await fetch(`${BACKEND_URL}/api/honeypot/detect`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'x-api-key': API_KEY
            },
            body: JSON.stringify(req.body)
        });

        const data = await response.json();
        res.status(response.status).json(data);
    } catch (error) {
        console.error('Proxy error (detect):', error);
        res.status(500).json({ error: error.message });
    }
});

// Proxy GET /logs to FastAPI
router.get('/logs', async (req, res) => {
    try {
        const response = await fetch(`${BACKEND_URL}/api/honeypot/logs`, {
            method: 'GET',
            headers: {
                'x-api-key': API_KEY
            }
        });

        const data = await response.json();
        res.status(response.status).json(data);
    } catch (error) {
        console.error('Proxy error (logs):', error);
        res.status(500).json({ error: error.message });
    }
});

// Proxy GET /sessions to FastAPI
router.get('/sessions', async (req, res) => {
    try {
        const response = await fetch(`${BACKEND_URL}/api/honeypot/sessions`, {
            method: 'GET',
            headers: {
                'x-api-key': API_KEY
            }
        });

        const data = await response.json();
        res.status(response.status).json(data);
    } catch (error) {
        console.error('Proxy error (sessions):', error);
        res.status(500).json({ error: error.message });
    }
});

// Proxy GET /session/:id/output to FastAPI
router.get('/session/:id/output', async (req, res) => {
    try {
        const response = await fetch(`${BACKEND_URL}/api/honeypot/session/${req.params.id}/output`, {
            method: 'GET',
            headers: {
                'x-api-key': API_KEY
            }
        });

        const data = await response.json();
        res.status(response.status).json(data);
    } catch (error) {
        console.error('Proxy error (session output):', error);
        res.status(500).json({ error: error.message });
    }
});

// Proxy POST /session/:id/timeout to FastAPI
router.post('/session/:id/timeout', async (req, res) => {
    try {
        const response = await fetch(`${BACKEND_URL}/api/honeypot/session/${req.params.id}/timeout`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'x-api-key': API_KEY
            }
        });

        const data = await response.json();
        res.status(response.status).json(data);
    } catch (error) {
        console.error('Proxy error (session timeout):', error);
        res.status(500).json({ error: error.message });
    }
});

module.exports = router;

