import '@fontsource/bangers/400.css';
import '@fontsource/press-start-2p/latin-400.css';
import '@fontsource/space-mono/400.css';
import './styles.css';
import './pixel-ui.css';

import { GameApp } from './app/gameApp';
import { registerPwaAfterLoad } from './platform/pwa';

const appUi = document.querySelector<HTMLElement>('#app-ui');
const canvas = document.querySelector<HTMLCanvasElement>('#game-canvas');

if (appUi === null || canvas === null) {
  throw new Error('Missing $SANIC bootstrap targets');
}

const app = new GameApp(canvas, appUi);
const initialization = app.initialize();

if (import.meta.env.MODE === 'production') {
  registerPwaAfterLoad(
    import.meta.env.MODE,
    initialization.then(() => appUi.dataset.phase === 'intro'),
  );
}
void initialization;

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
