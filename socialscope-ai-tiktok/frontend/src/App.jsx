import { useEffect, useState } from 'react';
import Layout from './components/Layout.jsx';
import { getHealth } from './api.js';
import Overview from './pages/Overview.jsx';
import UrlAnalyzer from './pages/UrlAnalyzer.jsx';
import CommentAnalysis from './pages/CommentAnalysis.jsx';
import Coordination from './pages/Coordination.jsx';
import Reports from './pages/Reports.jsx';
import About from './pages/About.jsx';

export default function App() {
  const [page, setPage] = useState('overview');
  const [health, setHealth] = useState(null);
  const [analysis, setAnalysis] = useState(null); // held in memory only; nothing is persisted in the browser

  useEffect(() => {
    getHealth().then(setHealth).catch((e) => setHealth({ error: e.message }));
  }, []);

  const props = { analysis, health, onNavigate: setPage };
  const pages = {
    overview: <Overview {...props} />,
    url: <UrlAnalyzer {...props} />,
    comments: <CommentAnalysis {...props} setAnalysis={setAnalysis} />,
    coordination: <Coordination {...props} />,
    reports: <Reports {...props} />,
    about: <About {...props} />,
  };
  return (
    <Layout page={page} onNavigate={(p) => { setPage(p); window.scrollTo(0, 0); }} health={health} dataSource={analysis?.data_source.filename}>
      {pages[page]}
    </Layout>
  );
}
