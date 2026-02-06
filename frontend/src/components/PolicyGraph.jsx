import './PolicyGraph.css';
import { useContext } from 'react';
import { DataContext } from '../DataContext';

function PolicyGraph() {
  const { parsedData } = useContext(DataContext);

  if (!parsedData) return <div className="policy-container">No data to display. Please upload a file first.</div>;
  
  return (
    <div className="policy-container">
      <h2> This is the scraped data from the uploaded file:</h2>
      <p className="parsed-data">
        {JSON.stringify(parsedData, null, 2)}
      </p>
    </div>
  );
}

export default PolicyGraph;