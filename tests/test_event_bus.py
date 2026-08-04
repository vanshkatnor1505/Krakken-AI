from core.events.event_bus import Event, event_bus


def on_message(event: Event) -> None:
    print(f"Received: {event.name}")
    print(event.payload)


event_bus.subscribe("chat.message", on_message)

event_bus.publish(
    Event(
        name="chat.message",
        payload={
            "user": "Vansh",
            "message": "Hello Kraken",
        },
    )
)