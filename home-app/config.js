/* Public defaults. Copy to config.local.js for personal settings; that file
   is ignored by Git and is embedded instead of this file at build/install time. */
var HomeConfig = {
    utcOffsetMinutes: 0, // Clock defaults to UTC. Set a fixed local offset.
    euSummerTime: false, // true: add 60 minutes during EU summer time (late March to late October).
    clock24h: false, // true: show 18:30 instead of 6:30 PM.
    // Optional Gira X1 controls via gira_bridge.py. Example (in config.local.js):
    // smartHome: {
    //     bridge: 'http://192.168.1.20:8770',
    //     lights: [{name: 'Ceiling', dp: 'a001', brightness: 'a002'}],      // brightness optional
    //     blinds: [{name: 'Blind', position: 'a003', slat: 'a004', upDown: 'a005', stop: 'a006'}],
    //     climate: {current: 'a007', setpoint: 'a008'}                      // display only
    // },
    smartHome: null,
    prayers: {
        enabled: false, // No calendar requests until explicitly configured.
        latitude: null,
        longitude: null,
        timezone: 'UTC',
        method: 3,
        location: 'Your location',
        region: '',
        source: 'AlAdhan'
    }
};
