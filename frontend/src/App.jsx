import { useState } from 'react';
import './App.css';
import Presentation from './components/Presentation';
import Homepage from './components/Homepage';

function App() {
  return (
    <div className='app-container'>
      <Homepage />
      <Presentation />
    </div>
    
  );
}

export default App;