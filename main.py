from flask_socketio import SocketIO, emit
from app import app

socketio = SocketIO(app)

if __name__ == "__main__":
    socketio.run(app, debug=True)

@socketio.on('offer')
def handle_offer(data):
    emit('offer', data, broadcast=True)

@socketio.on('answer')
def handle_answer(data):
    emit('answer', data, broadcast=True)

@socketio.on('ice-candidate')
def handle_ice_candidate(data):
    emit('ice-candidate', data, broadcast=True)
