import React from 'react'
import { MdBusiness } from 'react-icons/md'

export default function Companies() {
  return (
    <div>
      <div className="section-header-card blue">
        <div>
          <h2>Total Companies</h2>
          <div className="big-num">3</div>
        </div>
        <MdBusiness size={64} style={{opacity: 0.3}} />
      </div>

      <div className="empty-state">
        <MdBusiness />
        <p>Company management module under construction.</p>
        <span style={{fontSize: '12px'}}>Will integrate with Oracle definitions.</span>
      </div>
    </div>
  )
}
