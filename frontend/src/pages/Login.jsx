import React, { useState } from 'react'
import { MdLock, MdLogin, MdArrowBack } from 'react-icons/md'
import { login } from '../api/client'
import { Link, useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'

export default function Login({ onLogin }) {
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    try {
      const res = await login(password)
      if (res.data.access_token) {
        localStorage.setItem('utas_token', res.data.access_token)
        toast.success('Authenticated as Master User')
        onLogin()
        navigate('/')
      } else {
        toast.error('Failed to log in.')
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Authentication Failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-container">
      <div className="login-card">
        <div className="login-header">
           <div className="logo-circle">UTAS</div>
           <h1>Master Access</h1>
           <p>Enter Master Password to unlock full configuration access</p>
        </div>
        
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 500 }}><MdLock /> Master Password</label>
            <input 
              type="password" 
              placeholder="Enter master password" 
              value={password} 
              onChange={e => setPassword(e.target.value)}
              required
            />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '30px' }}>
            <button type="submit" className="btn btn-primary login-btn" disabled={loading} style={{ margin: 0 }}>
              {loading ? 'Authenticating...' : <><MdLogin /> Authenticate</>}
            </button>
            
            <button 
              type="button" 
              onClick={() => navigate('/')} 
              className="btn" 
              style={{ 
                margin: 0, 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: 'center', 
                gap: '8px', 
                background: 'rgba(255,255,255,0.05)', 
                border: '1px solid var(--color-border)', 
                color: 'var(--color-text)',
                padding: '12px',
                borderRadius: '8px',
                fontWeight: 600,
                cursor: 'pointer'
              }}
            >
              <MdArrowBack /> Return to Dashboard
            </button>
          </div>
        </form>
        
        <div className="login-footer">
          &copy; {new Date().getFullYear()} UTAS Security
        </div>
      </div>


      <style jsx>{`
        .login-container {
          height: 100vh;
          width: 100vw;
          display: flex;
          align-items: center;
          justify-content: center;
          background: #f0f2f5;
        }
        .login-card {
          width: 400px;
          background: white;
          padding: 40px;
          border-radius: 12px;
          box-shadow: 0 10px 25px rgba(0,0,0,0.1);
        }
        .login-header {
          text-align: center;
          margin-bottom: 30px;
        }
        .logo-circle {
          width: 60px;
          height: 60px;
          background: var(--color-accent, #3b82f6);
          color: white;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          font-weight: bold;
          font-size: 1.2rem;
          margin: 0 auto 15px;
        }
        .login-header h1 {
          margin: 0;
          font-size: 1.5rem;
          color: #1a1a1a;
        }
        .login-header p {
          color: #666;
          font-size: 0.9rem;
          margin-top: 5px;
        }
        .login-btn {
          width: 100%;
          margin-top: 30px;
          padding: 12px;
          font-size: 1rem;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 10px;
        }
        .login-footer {
          text-align: center;
          margin-top: 30px;
          font-size: 0.8rem;
          color: #999;
        }
      `}</style>
    </div>
  )
}
