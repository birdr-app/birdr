self.addEventListener('push', (event) => {
  const data = event.data ? event.data.json() : {};
  const title = data.title || 'Motmot - Bird quiz';
  const options = {
    body: data.body || 'You got mail',
    icon: data.icon || '/images/birdr-logo.png',
    actions: data.actions || [],
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

// Handle notification click
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url = event.notification.data?.url || '/'; // Default URL or custom from payload
  event.waitUntil(clients.openWindow(url));
});
