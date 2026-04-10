import React from 'react'
import { MdPeople } from 'react-icons/md'

export default function Employees() {
  return (
    <div>
      <div className="section-header-card green">
        <div>
          <h2>Total Employees</h2>
          <div className="big-num">24</div>
        </div>
        <MdPeople size={64} style={{opacity: 0.3}} />
      </div>

      <div className="empty-state">
        <MdPeople />
        <p>Employee management module under construction.</p>
        <span style={{fontSize: '12px'}}>Will integrate with Oracle definitions.</span>
      </div>
    </div>
  )
}
