let lightValues = [];
let maxValue;
let socketConnected = false;

// Connect to WebSocket server
const protocol = 'wss:';
const url = 'micro-api.awdokku.site/'
const ws = new WebSocket(`${protocol}//${url}`);
ws.onopen = () => {
  console.log('Connected to server');

  // Join the eight-px stream
  const joinMsg = {
    type: 'join',
    stream: 'eight-px'
  };
  ws.send(JSON.stringify(joinMsg));
  console.log('Requesting to join eight-px stream...');
};

ws.onclose = () => {
  console.log('Disconnected from server');
  socketConnected = false;
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};

ws.onmessage = (event) => {
  // console.log('Message from server:', event.data);

  try {
    const data = JSON.parse(event.data);

    console.log(data);

    // Handle successful join confirmation
    if (data.type === 'joined') {
      socketConnected = true;
      console.log('Successfully joined stream:', data.stream);
    }

    // Handle incoming sensor data
    if (data.type === 'data' && data.values) {
      // console.log('Received 8-pixel data:', data.values);
      // TODO: Process the 8 pixel values
      // data.values is an array of 8 integers (0-65535)
      // data.max is 65535
      maxValue = data.max;
      lightValues = data.values;
    }
  } catch (error) {
    console.error('Error parsing message:', error);
  }
};

