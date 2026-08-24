window.ARCH_DATA = window.ARCH_DATA || {};
window.ARCH_DATA["module-boundaries"] = {
  modules: {
    "user": {
      name: "用户域", description: "账号、身份与权限管理", note: "示例模块：项目按需增删。",
      ownsEntities: ["User", "Role", "Permission"],
      applicationService: { UserAppService: { methods: ["createUser(dto)","disableUser(id)"] } },
      events: {
        publishes: [{ event: "UserCreated", fields: "id, name, roleSlug", desc: "用户创建成功后发布" }],
        subscribes: [{ event: "BookingCreated", handler: "onBookingCreated", desc: "新订单触发用户积分" }]
      },
      crossModuleCalls: [{ target: "booking", via: "BookingCommandClient", methods: ["book"], reason: "下单校验" }],
      databaseOwnership: "user-db", independentDeployable: true
    },
    "booking": {
      name: "预订域", description: "预订与状态流转", ownsEntities: ["Booking"],
      applicationService: { BookingAppService: { methods: ["book(dto)","cancel(id)"] } },
      events: { publishes: [{ event: "BookingCreated", fields: "id, userId", desc: "" }], subscribes: [] },
      crossModuleCalls: [], databaseOwnership: "booking-db", independentDeployable: true
    }
  }
};