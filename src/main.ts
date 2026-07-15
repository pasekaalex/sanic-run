import '@fontsource/bangers/400.css';
import '@fontsource/space-mono/400.css';
import './styles.css';

import { GameApp } from './app/gameApp';

const appUi = document.querySelector<HTMLElement>('#app-ui');
const canvas = document.querySelector<HTMLCanvasElement>('#game-canvas');

if (appUi === null || canvas === null) {
  throw new Error('Missing $SANIC bootstrap targets');
}

const app = new GameApp(canvas, appUi);
void app.initialize();

const handlePageHide = (event: PageTransitionEvent): void => {
  if (!event.persisted) app.destroy();
};

window.addEventListener('pagehide', handlePageHide);

if (import.meta.hot) {
  import.meta.hot.dispose(() => {
    window.removeEventListener('pagehide', handlePageHide);
    app.destroy();
  });
}
