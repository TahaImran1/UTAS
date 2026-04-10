import React from 'react'

export default function StatCard({ title, value, color, icon: Icon }) {
  return (
    <div className={`stat-card ${color}`}>
      <div>
        <div className="label">{title}</div>
        <div className="value">{value}</div>
      </div>
      <div className="icon-box">
        {Icon && <Icon />}
      </div>
    </div>
  )
}
