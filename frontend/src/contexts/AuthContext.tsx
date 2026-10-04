import { createContext, useContext, useState, useEffect } from 'react'
import { api } from '../api'

interface AuthContextType {
  isAuthenticated: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  changePassword: (current: string, newPass: string) => Promise<void>
}

const AuthContext = createContext<AuthContextType | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false)

  useEffect(() => {
    const token = localStorage.getItem('sysvault_token')
    setIsAuthenticated(!!token)
  }, [])

  const login = async (username: string, password: string) => {
    const res = await api.login(username, password)
    localStorage.setItem('sysvault_token', res.access_token)
    setIsAuthenticated(true)
  }

  const logout = () => {
    localStorage.removeItem('sysvault_token')
    setIsAuthenticated(false)
    window.location.href = '/login'
  }

  const changePassword = async (current: string, newPass: string) => {
    await api.changePassword(current, newPass)
  }

  return (
    <AuthContext.Provider value={{ isAuthenticated, login, logout, changePassword }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
