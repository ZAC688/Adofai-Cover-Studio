import { createRoot } from 'react-dom/client';
import App from './App';
import {installDownloads} from './services/downloads';
installDownloads();
createRoot(document.getElementById('root')!).render(<App/>);
