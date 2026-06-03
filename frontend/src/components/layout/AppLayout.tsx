import { Layout, Menu } from 'antd';
import { DashboardOutlined, HistoryOutlined, BarChartOutlined, ThunderboltOutlined } from '@ant-design/icons';
import { useNavigate, useLocation } from 'react-router-dom';

const { Sider, Content } = Layout;

const menuItems = [
  { key: '/', icon: <DashboardOutlined />, label: '实时金价' },
  { key: '/history', icon: <HistoryOutlined />, label: '详细走势分析' },
  { key: '/factors', icon: <BarChartOutlined />, label: '因素分析' },
  { key: '/prediction', icon: <ThunderboltOutlined />, label: 'AI预测' },
];

interface Props {
  children: React.ReactNode;
}

export default function AppLayout({ children }: Props) {
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        width={200}
        style={{
          background: '#001529',
          overflow: 'auto',
          height: '100vh',
          position: 'fixed',
          left: 0,
          top: 0,
          bottom: 0,
        }}
      >
        <div style={{
          padding: '20px 16px 12px',
          textAlign: 'center',
          borderBottom: '1px solid rgba(255,255,255,0.1)',
          marginBottom: 8,
        }}>
          <img src="/logo.png" alt="Logo" style={{ width: 48, height: 48, borderRadius: '50%', marginBottom: 10 }} />
          <div style={{ color: '#ffd700', fontSize: 15, fontWeight: 700 }}>
            LuoY的金价分析
          </div>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
          style={{ fontSize: 14, borderRight: 0 }}
        />
      </Sider>
      <Layout style={{ marginLeft: 200 }}>
        <Content style={{ padding: '24px 32px', maxWidth: 2000, margin: '0 auto', width: '100%' }}>
          {children}
        </Content>
      </Layout>
    </Layout>
  );
}
