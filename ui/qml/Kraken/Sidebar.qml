import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import Kraken

Rectangle {

    id: root

    // ----------------------------------------------------------
    // Layout state
    // ----------------------------------------------------------

    property bool expanded: false

    property real expandedWidth: 220

    implicitWidth: root.expanded ? root.expandedWidth : Theme.sidebarWidth

    Behavior on implicitWidth {
        NumberAnimation {
            duration: Theme.medium
            easing.type: Easing.OutCubic
        }
    }

    color: Theme.surface

    border.color: Theme.border
    border.width: 1

    clip: true

    // ----------------------------------------------------------
    // Keyboard interaction
    // ----------------------------------------------------------

    focus: true
    activeFocusOnTab: true

    Keys.onDownPressed: root.selectedIndex = Math.min(root.selectedIndex + 1, root.navigationItems.length - 1)
    Keys.onUpPressed: root.selectedIndex = Math.max(root.selectedIndex - 1, 0)

    Keys.onReturnPressed: root.activate(root.selectedIndex)
    Keys.onEnterPressed: root.activate(root.selectedIndex)
    Keys.onSpacePressed: root.activate(root.selectedIndex)

    function activate(index) {

        root.selectedIndex = index

        root.itemSelected(index, root.navigationItems[index].label)
    }

    // ----------------------------------------------------------
    // Public signal — wire this to real navigation logic
    // ----------------------------------------------------------

    signal itemSelected(int index, string label)

    // ----------------------------------------------------------
    // Navigation model
    //
    // "badge" is opt-in per item (defaults false). Set it true
    // once there's a real pending-count/notification source to
    // bind to — this only controls whether the dot renders.
    // ----------------------------------------------------------

    readonly property var navigationItems: [
        { icon: "⌂", label: "Chat", badge: false },
        { icon: "◈", label: "Memory", badge: false },
        { icon: "⌘", label: "Automation", badge: false },
        { icon: "◉", label: "Vision", badge: false },
        { icon: "◌", label: "Voice", badge: false },
        { icon: "◇", label: "Plugins", badge: false },
        { icon: "⚙", label: "Settings", badge: false }
    ]

    property int selectedIndex: 0

    readonly property real itemHeight: 56
    readonly property real itemSpacing: Theme.spacingM

    // ----------------------------------------------------------
    // Footer status
    //
    // Bindable like TopBar/StatusBar — bind footerStatusText /
    // footerStatusState to a real source later, no changes
    // needed here.
    // ----------------------------------------------------------

    property string footerStatusText: "ONLINE"
    property string footerStatusState: "success"

    readonly property color footerStatusColor: {

        switch (root.footerStatusState) {

        case "success":
            return Theme.accentGreen

        case "warning":
            return Theme.warning

        case "danger":
            return Theme.danger

        default:
            return Theme.accent
        }
    }

    // ----------------------------------------------------------
    // Sliding selection indicator
    // ----------------------------------------------------------

    Rectangle {

        width: 3
        height: 34

        radius: 2

        x: 0

        y: navColumn.y
           + root.selectedIndex * (root.itemHeight + root.itemSpacing)
           + (root.itemHeight - height) / 2

        color: Theme.accent

        Behavior on y {
            NumberAnimation {
                duration: 240
                easing.type: Easing.OutCubic
            }
        }
    }

    // ----------------------------------------------------------
    // Navigation
    // ----------------------------------------------------------

    Column {

        id: navColumn

        anchors.top: parent.top
        anchors.topMargin: Theme.spacingXL

        anchors.left: parent.left
        anchors.right: parent.right

        anchors.leftMargin: Theme.spacingS
        anchors.rightMargin: Theme.spacingS

        spacing: root.itemSpacing

        Repeater {

            model: root.navigationItems

            delegate: Rectangle {

                id: navigationItem

                width: navColumn.width
                height: root.itemHeight

                radius: Theme.radiusMedium

                color: {

                    if (index === root.selectedIndex)
                        return Theme.accent

                    if (mouseArea.containsMouse)
                        return Theme.surfaceHover

                    return "transparent"
                }

                border.width: index === root.selectedIndex && root.activeFocus ? 1 : 0
                border.color: Theme.accent

                Behavior on color {
                    ColorAnimation {
                        duration: Theme.fast
                    }
                }

                // --------------------------------------------------
                // Icon
                // --------------------------------------------------

                Text {

                    id: icon

                    x: root.expanded
                       ? Theme.spacingM
                       : (parent.width - width) / 2

                    anchors.verticalCenter: parent.verticalCenter

                    text: modelData.icon

                    color: {

                        if (index === root.selectedIndex)
                            return Theme.background

                        if (mouseArea.containsMouse)
                            return Theme.textPrimary

                        return Theme.textSecondary
                    }

                    font.pixelSize: 24

                    Behavior on x {
                        NumberAnimation {
                            duration: Theme.medium
                            easing.type: Easing.OutCubic
                        }
                    }

                    Behavior on color {
                        ColorAnimation {
                            duration: Theme.fast
                        }
                    }
                }

                // --------------------------------------------------
                // Badge (opt-in per item)
                // --------------------------------------------------

                Rectangle {

                    visible: modelData.badge === true

                    width: 8
                    height: 8

                    radius: 4

                    x: icon.x + icon.width - 2
                    y: icon.y - 2

                    color: Theme.danger

                    border.width: 1.5
                    border.color: navigationItem.color === Theme.accent
                                  ? Theme.accent
                                  : Theme.surface
                }

                // --------------------------------------------------
                // Label (shown inline when expanded)
                // --------------------------------------------------

                Text {

                    anchors.left: icon.right
                    anchors.leftMargin: Theme.spacingM
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.right: parent.right
                    anchors.rightMargin: Theme.spacingS

                    elide: Text.ElideRight

                    text: modelData.label

                    color: index === root.selectedIndex
                           ? Theme.background
                           : Theme.textPrimary

                    font.pixelSize: Theme.fontBody
                    font.bold: index === root.selectedIndex

                    opacity: root.expanded ? 1 : 0

                    visible: opacity > 0.01

                    Behavior on opacity {
                        NumberAnimation {
                            duration: Theme.fast
                        }
                    }
                }

                // --------------------------------------------------
                // Tooltip (only needed when the label is hidden)
                // --------------------------------------------------

                Rectangle {

                    visible: !root.expanded && mouseArea.containsMouse

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

                    // small pointer arrow
                    Rectangle {
                        width: 8
                        height: 8
                        rotation: 45
                        color: parent.color
                        border.width: 1
                        border.color: Theme.border
                        anchors.right: parent.left
                        anchors.rightMargin: -4
                        anchors.verticalCenter: parent.verticalCenter
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

                        root.forceActiveFocus()

                        root.activate(index)
                    }
                }
            }
        }
    }

    // ----------------------------------------------------------
    // Expand / collapse toggle
    // ----------------------------------------------------------

    Rectangle {

        id: expandToggle

        width: 28
        height: 28

        radius: 14

        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: statusRow.top
        anchors.bottomMargin: Theme.spacingL

        color: toggleArea.containsMouse ? Theme.surfaceHover : "transparent"

        border.width: 1
        border.color: Theme.border

        Behavior on color {
            ColorAnimation {
                duration: Theme.fast
            }
        }

        Text {

            anchors.centerIn: parent

            text: "‹"

            color: Theme.textSecondary

            font.pixelSize: 16
            font.bold: true

            rotation: root.expanded ? 180 : 0

            Behavior on rotation {
                NumberAnimation {
                    duration: Theme.medium
                    easing.type: Easing.OutCubic
                }
            }
        }

        MouseArea {

            id: toggleArea

            anchors.fill: parent

            hoverEnabled: true

            cursorShape: Qt.PointingHandCursor

            onClicked: root.expanded = !root.expanded
        }
    }

    // ----------------------------------------------------------
    // Bottom status indicator
    // ----------------------------------------------------------

    Row {

        id: statusRow

        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: Theme.spacingL

        spacing: Theme.spacingS

        Rectangle {

            width: 8
            height: 8

            radius: 4

            anchors.verticalCenter: parent.verticalCenter

            color: root.footerStatusColor

            Behavior on color {
                ColorAnimation {
                    duration: Theme.medium
                }
            }

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

        Text {

            text: root.footerStatusText

            color: root.footerStatusColor

            font.pixelSize: Theme.fontSmall
            font.bold: true

            anchors.verticalCenter: parent.verticalCenter

            opacity: root.expanded ? 1 : 0

            visible: opacity > 0.01

            Behavior on opacity {
                NumberAnimation {
                    duration: Theme.fast
                }
            }
        }
    }
}
