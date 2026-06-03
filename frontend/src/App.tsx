import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import AppLayout from './components/layout/AppLayout';
import Dashboard from './pages/Dashboard';
import HistoricalCharts from './pages/HistoricalCharts';
import FactorAnalysis from './pages/FactorAnalysis';
import Prediction from './pages/Prediction';

function PageWrapper({ children }: { children: React.ReactNode }) {
  return <AppLayout>{children}</AppLayout>;
}

export default function App() {
  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: {
          colorPrimary: '#1677ff',
          borderRadius: 8,
        },
      }}
    >
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<PageWrapper><Dashboard /></PageWrapper>} />
          <Route path="/history" element={<PageWrapper><HistoricalCharts /></PageWrapper>} />
          <Route path="/factors" element={<PageWrapper><FactorAnalysis /></PageWrapper>} />
          <Route path="/prediction" element={<PageWrapper><Prediction /></PageWrapper>} />
        </Routes>
      </BrowserRouter>
    </ConfigProvider>
  );
}
