console.log("sketching bro");

let values = [];
let cellWidth, cellHeight;
let numRows = 4, numCols = 4;

function setup() {
  // createCanvas(windowWidth, windowHeight);
  createCanvas(800, 800);
  cellHeight = height/4; //since there will be 8 values
  cellWidth = width/4
  // let numCols = width; //this won't be exact on fullscreen!
  // cellWidth = width/numCols; //roughly square

  noStroke();
  noLoop();
}

function draw() {
  background(220);
  // console.log(forceValue);

  if(values.length){
    //draw the grid from the values!
    for(let row = 0; row < numRows; row++){
      for(let col = 0; col < numCols; col++){
        let index = row * numRows + col;
        let x = col * cellWidth;
        let y = row * cellHeight;
        fill(values[index]);
        rect(x, y, cellWidth + 1, cellHeight + 1); //plus one hack
      }
    }
  } else {
    text("waiting for incoming data from server", 20, 20);
  }
}

function handleReading(rawValues){

  values = []; //clear values

  for(let raw of rawValues){
    let c = map(raw, 0, maxValue, 0, 255);
    values.push(c); //update values
  }


  redraw();
}
