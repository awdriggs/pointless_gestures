console.log("sketching bro");
let cellSize;

function setup() {
  createCanvas(windowWidth, windowHeight);
  // createCanvas(100, 800);
  cellHeight = height/8; //since there will be 8 values
}

function draw() {
  background(220);
  // console.log(forceValue);

  for(let i = 0; i < lightValues.length; i++){
    
    fill(map(lightValues[i], 0, maxValue, 0, 255));
    rect(0, i * cellHeight, width, cellHeight);
  }
}
