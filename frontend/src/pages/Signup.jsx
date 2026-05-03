import React, { useState } from 'react'
import { MdLock, MdPerson, MdAssignmentInd, MdArrowBack } from 'react-icons/md'
import { register } from '../api/client'
import { Link, useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'

export default function Signup() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (password !== confirmPassword) {
      toast.error('Passwords do not match')
      return
    }
    
    setLoading(true)
    try {
      await register(username, password)
      toast.success('Registration successful! Please login.')
      navigate('/login')
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Registration failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-container">
      <div className="login-card">
        <div className="login-header">
           <div className="logo-circle">UTAS</div>
           <h1>Create Account</h1>
           <p>Register a new administrator account</p>
        </div>
        
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label><MdPerson /> Username</label>
            <input 
              type="text" 
              placeholder="Choose a username" 
              value={username} 
              onChange={e => setUsername(e.target.value)}
              required
            />
          </div>

          <div className="form-group" style={{marginTop: '20px'}}>
            <label><MdLock /> Password</label>
            <input 
              type="password" 
              placeholder="Create a password" 
              value={password} 
              onChange={e => setPassword(e.target.value)}
              required
            />
          </div>

          <div className="form-group" style={{marginTop: '20px'}}>
            <label><MdLock /> Confirm Password</label>
            <input 
              type="password" 
              placeholder="Repeat password" 
              value={confirmPassword} 
              onChange={e => setConfirmPassword(e.target.value)}
              required
            />
          </div>

          <button type="submit" className="btn btn-primary login-btn" disabled={loading}>
            {loading ? 'Registering...' : <><MdAssignmentInd /> Sign Up</>}
          </button>
        </form>
        
        <div className="login-footer">
          <Link to="/login" style={{display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '5px', textDecoration: 'none', color: 'var(--color-accent)'}}>
            <MdArrowBack /> Back to Login
          </Link>
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
          font-size: 0.9rem;
        }
      `}</style>
    </div>
  )
}
