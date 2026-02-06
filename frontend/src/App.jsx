import './App.css';
import { useState } from 'react';
import { DataContext } from './DataContext';
import Homepage from './components/Homepage';
import PolicyGraph from './components/PolicyGraph';

function App() {
  const [parsedData, setParsedData] = useState(null);

  return (
    <DataContext.Provider value={{ parsedData, setParsedData }}>
      <div className='app-container'>
        <div className='ai-container'>
          <Homepage />
        </div>
        <div className='active-tab-container'>
          <PolicyGraph />
        </div>
      </div>
    </DataContext.Provider>
  );
}

export default App;