import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { installThemeVars } from './design/tokens';
import App from './App';
import './index.css';

// Inject the design-token CSS custom properties into <head> before the first paint so light/dark
// theming is resolved by the cascade with no flash of unstyled content.
installThemeVars();

const rootEl = document.getElementById('root');
if (!rootEl) throw new Error('citeval: #root element not found');

createRoot(rootEl).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
