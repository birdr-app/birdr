import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'pro.birdr',
  appName: 'Motmot',
  webDir: 'build',
  server: {
    url: 'https://motmot.club',
    cleartext: false
  }
};

export default config;
