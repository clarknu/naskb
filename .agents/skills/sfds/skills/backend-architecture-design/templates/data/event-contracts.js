window.ARCH_DATA = window.ARCH_DATA || {};
window.ARCH_DATA["event-contracts"] = {
  totalDomainEvents: 2, totalCommands: 1,
  eventRegistry: {
    DomainEvents: {
      "UserCreated": { producer: "user/application", consumers: ["booking/application"], fields: { id: "guid", name: "string" } },
      "BookingCreated": { producer: "booking/application", consumers: ["user/application"], fields: "id, userId" }
    },
    Commands: {
      "CancelBooking": { producer: "booking/application", consumer: "user/application", fields: { bookingId: "guid", reason: "string" } }
    }
  }
};