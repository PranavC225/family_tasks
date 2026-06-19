function urlBase64ToUint8Array(b) {
  const pad = '='.repeat((4 - (b.length % 4)) % 4);
  const s = (b + pad).replace(/-/g, '+').replace(/_/g, '/');
  return Uint8Array.from([...atob(s)].map((c) => c.charCodeAt(0)));
}

async function enableNotifications() {
  if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
    alert('Push not supported on this device/browser.');
    return;
  }
  const reg = await navigator.serviceWorker.register('/sw.js');
  if ((await Notification.requestPermission()) !== 'granted') {
    alert('Notifications blocked.');
    return;
  }
  const { key } = await (await fetch('/push/vapid-public-key')).json();
  const sub = await reg.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(key),
  });
  const resp = await fetch('/push/subscribe', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(sub),
  });
  alert(resp.ok ? 'Notifications enabled.' : 'Could not save subscription.');
}

document.addEventListener('DOMContentLoaded', () => {
  const btn = document.getElementById('enable-notifications');
  if (btn) btn.addEventListener('click', enableNotifications);
});
