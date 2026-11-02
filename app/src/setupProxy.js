const { createProxyMiddleware } = require('http-proxy-middleware');

module.exports = function (app) {
  const target =
    process.env.REACT_APP_API_URL ||
    (process.env.NODE_ENV === 'development' ? 'http://127.0.0.1:8050' : 'https://motmot.club');

  const proxyOptions = {
    target,
    logLevel: 'debug',
    secure: false,
    onError: (err, req, res) => {
      console.error('Proxy error:', err.message);
      console.error('Target:', target);
      console.error('Request URL:', req.url);
      res.status(500).json({
        error: 'Proxy error',
        message: err.message,
        target,
        url: req.url,
      });
    },
    onProxyReq: (proxyReq, req, res) => {
      console.log('Proxying request:', req.method, req.url, '->', target + req.url);
    },
  };

  app.use(
    ['/api', '/admin', '/token', '/django', '/auth', '/media', '/g', '/flocks/results', '/flocks/c'],
    createProxyMiddleware({
      ...proxyOptions,
      changeOrigin: true,
    })
  );

  // Public marketing HTML from Django (do not proxy `/` — CRA needs it for the app).
  app.use(
    [
      '/site',
      '/data',
      '/how-it-works',
      '/bird-identification-quiz',
      '/learn-bird-identification',
      '/bird-quiz-by-country',
      '/birding-app',
      '/my-tricky-birds',
      '/countries',
      '/birds',
      '/compare',
      '/page',
      '/sitemap.xml',
      '/sitemap-pages.xml',
      '/sitemap-countries.xml',
      '/sitemap-birds.xml',
      '/sitemap-compare.xml',
      '/robots.txt',
    ],
    createProxyMiddleware({
      ...proxyOptions,
      changeOrigin: true,
    })
  );
};
