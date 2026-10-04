import { Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import EntryPage from './pages/EntryPage'
import EditEntryPage from './pages/EditEntryPage'
import SearchPage from './pages/SearchPage'
import BackupPage from './pages/BackupPage'
import ExportPage from './pages/ExportPage'
import AssetsPage from './pages/AssetsPage'
import EmployeesPage from './pages/EmployeesPage'
import MainLayout from './components/MainLayout'
import { AppProvider } from './contexts/AppContext'

function AuthenticatedRoutes() {
  return (
    <Routes>
      <Route path="/" element={<MainLayout><DashboardPage /></MainLayout>} />
      <Route path="/entry/:id" element={<MainLayout><EntryPage /></MainLayout>} />
      <Route path="/new" element={<MainLayout><EditEntryPage /></MainLayout>} />
      <Route path="/edit/:id" element={<MainLayout><EditEntryPage /></MainLayout>} />
      <Route path="/search" element={<MainLayout><SearchPage /></MainLayout>} />
      <Route path="/category/:categoryId" element={<MainLayout><DashboardPage /></MainLayout>} />
      <Route path="/favorites" element={<MainLayout><DashboardPage /></MainLayout>} />
      <Route path="/recent" element={<MainLayout><DashboardPage /></MainLayout>} />
      <Route path="/backup" element={<MainLayout><BackupPage /></MainLayout>} />
      <Route path="/export" element={<MainLayout><ExportPage /></MainLayout>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

function AppContent() {
  const { isAuthenticated } = useAuth()
  if (!isAuthenticated) return <LoginPage />
  return <AuthenticatedRoutes />
}

export default function App() {
  return (
    <AuthProvider>
      <AppProvider>
        <AppContent />
      </AppProvider>
    </AuthProvider>
  )
}
