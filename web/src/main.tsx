import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import { StationProvider, createApi } from './api/station'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <StationProvider api={createApi()}>
      <App />
    </StationProvider>
  </React.StrictMode>,
)
