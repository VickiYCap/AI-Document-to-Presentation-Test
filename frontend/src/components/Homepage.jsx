import './Homepage.css';
function Homepage() {
  return (
    <>
    <div className='homepage-container'>
      <h1>Welcome!</h1>
      <h2>What can I help with? </h2>
      <div className='search-query'>
        <input className='input-bar'></input>
        <button className='search-button'>Search</button>
      </div>
        <div style={{marginTop:"30px"}}> OR </div>
        <div className='file-upload'>
          <div>Select a file to turn into a presentation</div>
          <form action = "/upload" method="post" encType="multipart/form-data">
            <input type="file" name="file"/>
            <input type="submit" value="Upload"/>
          </form>
        </div>

    </div>
    </>
  );
}

export default Homepage;