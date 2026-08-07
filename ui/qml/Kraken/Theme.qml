pragma Singleton

import QtQuick

QtObject {

    // ==========================================================
    // Application
    // ==========================================================

    readonly property string appName: "Krakken AI"

    // ==========================================================
    // Colors
    // ==========================================================

    readonly property color background: "#0A0E17"

    readonly property color surface: "#161F33"

    readonly property color surfaceLight: "#1E2A44"

    readonly property color surfaceHover: "#24314D"

    readonly property color accent: "#00D4FF"

    readonly property color accentPurple: "#8B5CF6"

    readonly property color accentGreen: "#00FFA3"

    readonly property color warning: "#FFC857"

    readonly property color danger: "#FF4D6D"

    readonly property color border: "#2B3957"

    readonly property color textPrimary: "#F8FAFC"

    readonly property color textSecondary: "#94A3B8"

    readonly property color textDisabled: "#64748B"

    // ==========================================================
    // Radius
    // ==========================================================

    readonly property int radiusSmall: 8

    readonly property int radiusMedium: 14

    readonly property int radiusLarge: 20

    readonly property int radiusXL: 28

    readonly property int radiusRound: 9999

    // ==========================================================
    // Spacing
    // ==========================================================

    readonly property int spacingXS: 4

    readonly property int spacingS: 8

    readonly property int spacingM: 12

    readonly property int spacingL: 16

    readonly property int spacingXL: 24

    readonly property int spacingXXL: 32

    // ==========================================================
    // Sizes
    // ==========================================================

    readonly property int sidebarWidth: 90

    readonly property int topBarHeight: 64

    readonly property int statusBarHeight: 42

    readonly property int commandBarHeight: 64

    readonly property int buttonHeight: 44

    readonly property int iconSize: 22

    // ==========================================================
    // Fonts
    // ==========================================================

    readonly property int fontSmall: 12

    readonly property int fontBody: 14

    readonly property int fontMedium: 16

    readonly property int fontTitle: 22

    readonly property int fontHero: 48

    // ==========================================================
    // Animation
    // ==========================================================

    readonly property int fast: 120

    readonly property int medium: 220

    readonly property int slow: 450

    readonly property int extraSlow: 900

    // ==========================================================
    // Opacity
    // ==========================================================

    readonly property real glassOpacity: 0.94

    readonly property real disabledOpacity: 0.45

    readonly property real hoverOpacity: 0.98

}