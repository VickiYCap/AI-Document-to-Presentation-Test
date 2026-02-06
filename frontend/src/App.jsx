import './App.css';
import { useState } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { DataContext } from './DataContext';

import Homepage from './components/Homepage';       
import PolicyGraph from './components/PolicyGraph'; 
import Presentation from './components/Presentation';
import Testing from './components/Testing';


function Blank() {
  return(
    <div className="landing-container">
      <h1>
        Ready to Create? 
      </h1>
      <h3> Upload a file to start or ask a question to start</h3>
    </div>
  )
};

function App() {
  const [parsedData, setParsedData] = useState(null);

  return (
    <DataContext.Provider value={{ parsedData, setParsedData }}>
      <Router>
        <div className="app-container">
          <aside className="ai-agent">
            <Homepage />
          </aside>

          <main className="active-tab-container">
            <Routes>
              <Route path="/" element={<Blank />} />
              <Route path="/policy-graph" element={<PolicyGraph />} />
              <Route path="/presentation" element={<Presentation />} />
              <Route path="/testing" element={<Testing />} />
            </Routes>
          </main>
        </div>
      </Router>
    </DataContext.Provider>
  );
}

export default App;