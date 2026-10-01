// Valet Parking PWA Header Initialization (Manifest & Mobile Meta Tags)

(function() {
    if (document.querySelector('link[rel="manifest"]')) return;

    // Inject Web App Manifest link
    var link = document.createElement('link');
    link.rel = 'manifest';
    link.href = '/assets/valet_parking/manifest.json';
    document.head.appendChild(link);

    // Inject theme-color meta tag
    var metaTheme = document.createElement('meta');
    metaTheme.name = 'theme-color';
    metaTheme.content = '#17a2b8';
    document.head.appendChild(metaTheme);

    // Inject mobile web app capable meta tags
    var metaApple = document.createElement('meta');
    metaApple.name = 'apple-mobile-web-app-capable';
    metaApple.content = 'yes';
    document.head.appendChild(metaApple);

    var metaMobile = document.createElement('meta');
    metaMobile.name = 'mobile-web-app-capable';
    metaMobile.content = 'yes';
    document.head.appendChild(metaMobile);

    var metaTitle = document.createElement('meta');
    metaTitle.name = 'apple-mobile-web-app-title';
    metaTitle.content = 'Valet';
    document.head.appendChild(metaTitle);
})();
