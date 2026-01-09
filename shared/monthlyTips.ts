/**
 * Monthly beekeeping tips shared between mobile and web
 */

export interface MonthlyTip {
  main: string;
  details: string[];
}

export const MONTHLY_TIPS: Record<number, MonthlyTip> = {
  0: { // January
    main: "Winter cluster management. Bees are in a tight cluster to maintain warmth, consuming 1-2 pounds of honey per day to keep internal temperature around 70°F.",
    details: [
      "Clear snow from hive entrance if present",
      "Emergency feeding with fondant patty if hives weigh less than 50-80 pounds",
      "Order bees and equipment for spring",
      "Check and repair beekeeping equipment",
      "On warm days (>50°F), bees may take cleansing flights"
    ]
  },
  1: { // February
    main: "Late winter monitoring. Bees continue clustering for warmth and may move around the hive to access honey stores.",
    details: [
      "Clear snow from hive entrance if present",
      "Emergency feeding with fondant patty if hives weigh less than 50-80 pounds",
      "Order bees and equipment for spring",
      "Check and repair beekeeping equipment",
      "On warm days (>50°F), bees may take cleansing flights"
    ]
  },
  2: { // March
    main: "Early spring awakening. Bees can starve during March due to low honey stores. Brood production increases, requiring more energy resources.",
    details: [
      "Check hive weight - bees can easily starve during this time",
      "Feed bees 1:1 sugar water syrup and pollen patty",
      "Remove winterizing gear when temperatures are consistently above freezing",
      "Get frame count on warm days (>55°F) - strong hives have 6+ frames with bees",
      "Change entrance reducer to larger size",
      "Test and treat for tracheal mites if suspected"
    ]
  },
  3: { // April
    main: "Spring buildup season. Brood increases rapidly with rising temperatures and pollen presence. Drones begin to be produced.",
    details: [
      "Full hive inspection on warm days (>55°F) - check all stages of brood",
      "Attempt to find the queen - populations are small and easier to spot",
      "Consider splitting overwintered hives to control population and reduce swarming risk",
      "Begin monthly check for foulbrood diseases",
      "Feed bees 1:1 sugar water syrup and pollen patty",
      "Register hives with Utah Department of Agriculture and Food (UDAF)"
    ]
  },
  4: { // May
    main: "Swarm season begins. Rapidly expanding bee populations can lead to swarming. Perform Varroa mite checks and treat if needed.",
    details: [
      "Full hive inspection - assess pollen and nectar stores",
      "Assess laying pattern and all stages of brood for queen health",
      "Do frame count to ensure populations are rising",
      "Feed 1:1 sugar water syrup to new colonies until nectar flow supports them",
      "Watch for and manage swarming behaviors - add boxes or split hives",
      "Add honey super when you have 7 full frames of capped honey in top box",
      "Varroa mite check - treat if more than 5 mites per 300 bees"
    ]
  },
  5: { // June
    main: "Peak nectar flow in Utah. Bees are busy foraging and bringing nectar back to the hive. Target 80-100 pounds of honey for winter stores.",
    details: [
      "Thorough hive inspection - assess laying pattern and all stages of brood",
      "Remove entrance reducer at beginning of month",
      "Watch for and manage swarming behaviors",
      "Add honey super when you have 7 full frames of capped honey in top box",
      "Move full and capped frames to outside of box to encourage filling empty frames"
    ]
  },
  6: { // July
    main: "High temperatures may cause bees to beard on outside of hive. Hive population at peak, making queen spotting difficult.",
    details: [
      "Full hive inspection - look for all stages of brood and capped nectar",
      "Ensure hive has access to water during hot, dry months",
      "Add honey super when you have 7 full frames of capped honey in top box",
      "If bees are bearding, improve ventilation with screened bottom board or prop lid open",
      "Continue to manage hive to prevent swarming",
      "Add supers as necessary"
    ]
  },
  7: { // August
    main: "Harvest season begins, and winter is coming. Established hives should have over 100 pounds of honey going into winter. Critical time for Varroa mite treatment.",
    details: [
      "Thorough hive inspection - assess laying pattern and queen strength",
      "Assess hive for brood diseases",
      "Check for Varroa mite - treat if more than 5 mites per 300 bees",
      "Begin honey harvest from supers if stores are abundant",
      "Don't over harvest - colony needs 100 pounds for winter stores"
    ]
  },
  8: { // September
    main: "Fall preparation begins. Hive slows down, bee populations diminish, and queen starts laying winter brood.",
    details: [
      "Thorough inspection - verify queen is laying",
      "Begin feeding 2:1 sugar water syrup with in-hive feeder",
      "Install robber screens or reduce entrance to discourage robbing",
      "Weigh hives - should be 80-100 pounds with 10-12 full deep frames of capped honey",
      "Continue monitoring and treating for Varroa mite"
    ]
  },
  9: { // October
    main: "Winter preparation intensifies. Bees are building population of overwintering bees with different physiology for cold temperatures.",
    details: [
      "Final full hive inspection if temperatures are warm",
      "Assess honey stores for winter, laying pattern and all stages of brood",
      "Feed 2:1 sugar water syrup until temperatures drop near freezing",
      "Wrap hives at high elevations or with little wind protection",
      "Ensure adequate air circulation to prevent condensation",
      "Change entrance reducer to smallest opening",
      "Install mouse guard and secure lid"
    ]
  },
  10: { // November
    main: "Deep winter management. Bees begin clustering at 57°F and shiver wing muscles to maintain hive temperature.",
    details: [
      "Be careful opening hive in cold temperatures",
      "If lifting lid is necessary, pick calm, warm day (>55°F) and work quickly",
      "Feed fondant patty if hive weight or honey stores are light",
      "Clear snow from hive entrance"
    ]
  },
  11: { // December
    main: "Minimal disturbance period. Bees should be disturbed as little as possible. Assess status by knocking on hive and listening for buzzing.",
    details: [
      "Feed fondant patty if hive weight or honey stores are light",
      "Clear snow from hive entrance",
      "Assess bee status by knocking on hive and listening for buzzing sound",
      "On warm days, bees may make quick cleansing flights"
    ]
  }
};

export const MONTH_NAMES = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'
];

