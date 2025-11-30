import { useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Header from './components/Header';
import LandingPage from './pages/LandingPage';
import Marketplace from './pages/Marketplace';
import ConnectWallet from './components/ConnectWallet';
import Issuer from './pages/Issuer';
import Profile from './pages/Profile';
import ApplyForAsset from './pages/ApplyForAsset';
import AdminDashboard from './pages/AdminDashboard';
import ProjectDetail from './pages/ProjectDetail';
import './App.css';
import './theme.css';

function App() {
  // Theme will be set by Header component from localStorage
  useEffect(() => {
    const savedTheme = localStorage.getItem('theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);
  }, []);

  return (
    <Router>
      <div className="App">
        <Header />
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/marketplace" element={<Marketplace />} />
          <Route path="/project/:projectId" element={<ProjectDetail />} />
          <Route path="/connect" element={<ConnectWallet />} />
          <Route path="/issuer" element={<Issuer />} />
          <Route path="/profile" element={<Profile />} />
          <Route path="/apply-asset" element={<ApplyForAsset />} />
          <Route path="/admin" element={<AdminDashboard />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;
