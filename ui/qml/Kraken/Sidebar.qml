
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import Kraken

Rectangle {

    id: root

    implicitWidth: Theme.sidebarWidth
    color: Theme.surface

    border.color: Theme.border
    border.width: 1

    // ----------------------------------------------------------
    // Navigation model
    // ----------------------------------------------------------

    readonly property var navigationItems: [
        { icon: "⌂", label: "Chat" },
        { icon: "◈", label: "Memory" },
        { icon: "⌘", label: "Automation" },
        { icon: "◉", label: "Vision" },
        { icon: "◌", label: "Voice" },
        { icon: "◇", label: "Plugins" },
        { icon: "⚙", label: "Settings" }
    ]

    property int selectedIndex: 0

    // ----------------------------------------------------------
    // Navigation
    // ----------------------------------------------------------

    Column {

        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        anchors.topMargin: Theme.spacingXL

        spacing: Theme.spacingM

        Repeater {

            model: root.navigationItems

            delegate: Rectangle {

                id: navigationItem

                width: 64
                height: 64

                radius: Theme.radiusMedium

                color: {

                    if (index === root.selectedIndex)
                        return Theme.accent

                    if (mouseArea.containsMouse)
                        return Theme.surfaceHover

                    return "transparent"
                }

                border.width: index === root.selectedIndex ? 1 : 0
                border.color: Theme.accent

                scale: mouseArea.pressed ? 0.94 : 1.0

                Behavior on color {
                    ColorAnimation {
                        duration: Theme.fast
                    }
                }

                Behavior on scale {
                    NumberAnimation {
                        duration: Theme.fast
                        easing.type: Easing.OutCubic
                    }
                }

                // --------------------------------------------------
                // Selection glow
                // --------------------------------------------------

                Rectangle {

                    visible: index === root.selectedIndex

                    width: 3
                    height: 34

                    radius: 2

                    anchors.left: parent.left
                    anchors.leftMargin: -1
                    anchors.verticalCenter: parent.verticalCenter

                    color: Theme.accent
                }

                // --------------------------------------------------
                // Icon
                // --------------------------------------------------

                Text {

                    anchors.centerIn: parent

                    text: modelData.icon

                    color: {

                        if (index === root.selectedIndex)
                            return Theme.background

                        if (mouseArea.containsMouse)
                            return Theme.textPrimary

                        return Theme.textSecondary
                    }

                    font.pixelSize: 24

                    Behavior on color {
                        ColorAnimation {
                            duration: Theme.fast
                        }
                    }
                }

                // --------------------------------------------------
                // Tooltip
                // --------------------------------------------------

                Rectangle {

                    visible: mouseArea.containsMouse

                    anchors.left: parent.right
                    anchors.leftMargin: Theme.spacingS
                    anchors.verticalCenter: parent.verticalCenter

                    width: tooltipText.implicitWidth + 24
                    height: 34

                    radius: Theme.radiusSmall

                    color: Theme.surfaceLight

                    border.width: 1
                    border.color: Theme.border

                    z: 100

                    opacity: visible ? 1 : 0

                    Behavior on opacity {
                        NumberAnimation {
                            duration: Theme.fast
                        }
                    }

                    Text {

                        id: tooltipText

                        anchors.centerIn: parent

                        text: modelData.label

                        color: Theme.textPrimary

                        font.pixelSize: Theme.fontBody
                    }
                }

                // --------------------------------------------------
                // Interaction
                // --------------------------------------------------

                MouseArea {

                    id: mouseArea

                    anchors.fill: parent

                    hoverEnabled: true

                    cursorShape: Qt.PointingHandCursor

                    onClicked: {

                        root.selectedIndex = index

                        console.log(
                            "Navigation:",
                            modelData.label
                        )
                    }
                }
            }
        }
    }

    // ----------------------------------------------------------
    // Bottom status indicator
    // ----------------------------------------------------------

    Rectangle {

        width: 8
        height: 8

        radius: 4

        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: Theme.spacingL

        color: Theme.accentGreen

        SequentialAnimation on opacity {

            loops: Animation.Infinite

            NumberAnimation {
                from: 1.0
                to: 0.35
                duration: 1000
            }

            NumberAnimation {
                from: 0.35
                to: 1.0
                duration: 1000
            }
        }
    }
}

