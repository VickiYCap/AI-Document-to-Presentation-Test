import { useState } from 'react';
import './App.css';
import Homepage from './components/Homepage';
import PolicyGraph from './components/PolicyGraph';

function App() {
  return (
    <div className='app-container'>
      <div className='ai-container'>
        <Homepage />
      </div>
      <div className='active-tab-container'>
        <PolicyGraph/>

      </div>
    </div>
    
  );
}

export default App;