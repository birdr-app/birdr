 export const requestNotificationPermission = () => {
    if ("Notification" in window) {
      Notification.requestPermission().then((permission) => {
        if (permission === "granted") {
          alert("You will receive notifications!");
        } else if (permission === "denied") {
          alert("You have denied notifications.");
        }
      });
    } else {
      alert("This browser does not support desktop notifications.");
    }
  };

export const sendNotification = async ({title, body}: {title: string, body: string}): Promise<void> => {
  if ('serviceWorker' in navigator) {
    const registration = await navigator.serviceWorker.ready;
    registration.showNotification('Motmot - Bird quiz', {
      body: 'Ready to identify some birds?',
      icon: '/images/logo.png',
      badge: '/images/badge.png',
      data: { url: 'https://birdr.pro/journey/intro' },
      actions: [
        { action: 'open', title: 'Open App' },
        { action: 'dismiss', title: 'Dismiss' },
      ],
    });
  } else {
    console.error('Service Worker is not supported in this browser.');
  }
};
