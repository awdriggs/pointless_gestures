console.log("sketching bro");
// let cellSize;
let w; //bar width

function setup() {
  createCanvas(windowWidth, windowHeight);
  // createCanvas(100, 800);
  // cellHeight = height/8; //since there will be 8 values
  noStroke();
}

function draw() {
  background(220);
  if(bars.length){
    w = width/bars.length;

    for(let i = 0; i < bars.length; i++){
      let rgb = bars[i];
      fill(rgb.r, rgb.g, rgb.b);
      rect(i * w, 0, w + 1, height); //plus one hack on width
    }
  } else {
    text("waiting for incoming values", 20, 20);
  }
}


