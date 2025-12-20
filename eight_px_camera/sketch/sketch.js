console.log("sketching bro");

let cols = [];
let cellWidth, cellHeight;

function setup() {
  createCanvas(windowWidth, windowHeight);
  // createCanvas(100, 800);
  cellHeight = height/8; //since there will be 8 values
  // let numCols = width; //this won't be exact on fullscreen!
  // cellWidth = width/numCols; //roughly square


  // for(let i = 0; i < numCols; i++){
  //   cols.push([255, 255, 255, 255, 255, 255, 255, 255]); //fill with data
  //   // cols.push([random(255), random(255), random(255), random(255), random(255), random(255), random(255), random(255)])
  // }

  noStroke();
  noLoop();

}

function draw() {
  background(220);
  // console.log(forceValue);

  if(cols.length){
    let cellWidth = width/cols.length;

    for(let i = 0; i < cols.length; i++){
      let x = i * cellWidth; //each col is a single pixel
      let col = cols[i];
      for(let j = 0; j < col.length; j++){
        let y = j * cellHeight;
        fill(col[j]);
        rect(x, y, cellWidth + 1, cellHeight + 1); //+1 is a hack to get rid of lines
      }
    }
  } else {
    text("waiting for incoming data from server", 20, 20);
  }
  // for(let i = 0; i < lightValues.length; i++){

  //   fill(map(lightValues[i], 0, maxValue, 0, 255));
  //   rect(0, i * cellHeight, width, cellHeight);
  // }
}

function handleReading(rawValues){

  let values = [];

  for(let raw of rawValues){
    let c = map(raw, 0, maxValue, 0, 255);
    values.push(c);
  }
  cols.push(values); //add the new reading

  if(cols.length > width){
    cols.shift(); //drop the oldest reading
  }

  redraw();
}
