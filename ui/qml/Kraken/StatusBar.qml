import QtQuick
import QtQuick.Layouts

import Kraken

Rectangle {

    id: root

    // ----------------------------------------------------------
    // Base
    // ----------------------------------------------------------

    implicitHeight: Theme.statusBarHeight

    color: Theme.surface

    border.color: Theme.border
    border.width: 1

    // ----------------------------------------------------------
    // Status data
    //
    // Each entry is exposed as its own bindable property so a
    // backend (context property, singleton, etc.) can bind to
    // it later without any changes needed here.
    //
    // e.g. root.cpuValue: SystemMonitor.cpuUsage + "%"
    // ----------------------------------------------------------

    property string cpuLabel: "CPU"
    property string cpuValue: "0%"
    property string cpuState: "normal"

    property string ramLabel: "RAM"
    property string ramValue: "0%"
    property string ramState: "normal"

    property string voiceLabel: "VOICE"
    property string voiceValue: "READY"
    property string voiceState: "success"

    property string aiLabel: "AI"
    property string aiValue: "ONLINE"
    property string aiState: "success"

    property string memoryLabel: "MEMORY"
    property string memoryValue: "READY"
    property string memoryState: "success"

    // Model built from the properties above. This recalculates
    // automatically whenever any of the bound properties change.
    readonly property var statusItems: [
        {
            label: cpuLabel,
            value: cpuValue,
            state: cpuState
        },
        {
            label: ramLabel,
            value: ramValue,
            state: ramState
        },
        {
            label: voiceLabel,
            value: voiceValue,
            state: voiceState
        },
        {
            label: aiLabel,
            value: aiValue,
            state: aiState
        },
        {
            label: memoryLabel,
            value: memoryValue,
            state: memoryState
        }
    ]

    // ----------------------------------------------------------
    // Status layout
    // ----------------------------------------------------------

    RowLayout {

        anchors.fill: parent

        anchors.leftMargin: Theme.spacingXL
        anchors.rightMargin: Theme.spacingXL

        spacing: Theme.spacingXXL

        Repeater {

            model: root.statusItems

            delegate: RowLayout {

                spacing: Theme.spacingS

                // ----------------------------------------------
                // Status indicator
                // ----------------------------------------------

                Rectangle {

                    Layout.alignment: Qt.AlignVCenter

                    width: 7
                    height: 7

                    radius: 3.5

                    color: {

                        switch (modelData.state) {

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

                    SequentialAnimation on opacity {

                        loops: Animation.Infinite

                        NumberAnimation {

                            from: 1.0
                            to: 0.45

                            duration: 1200
                        }

                        NumberAnimation {

                            from: 0.45
                            to: 1.0

                            duration: 1200
                        }
                    }
                }

                // ----------------------------------------------
                // Label
                // ----------------------------------------------

                Text {

                    text: modelData.label

                    color: Theme.textSecondary

                    font.pixelSize: Theme.fontSmall

                    font.bold: true

                    Layout.alignment: Qt.AlignVCenter
                }

                // ----------------------------------------------
                // Value
                // ----------------------------------------------

                Text {

                    text: modelData.value

                    color: {

                        switch (modelData.state) {

                        case "success":
                            return Theme.accentGreen

                        case "warning":
                            return Theme.warning

                        case "danger":
                            return Theme.danger

                        default:
                            return Theme.textPrimary
                        }
                    }

                    font.pixelSize: Theme.fontSmall

                    font.bold: true

                    Layout.alignment: Qt.AlignVCenter
                }
            }
        }

        Item {
            Layout.fillWidth: true
        }

        // ------------------------------------------------------
        // Kraken status
        // ------------------------------------------------------

        RowLayout {

            spacing: Theme.spacingS

            Rectangle {

                width: 7
                height: 7

                radius: 3.5

                color: Theme.accentGreen
            }

            Text {

                text: "KRAKKEN CORE"

                color: Theme.textSecondary

                font.pixelSize: Theme.fontSmall

                font.bold: true
            }
        }
    }
}
