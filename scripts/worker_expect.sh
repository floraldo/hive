#!/usr/bin/env expect -f
#
# worker_expect.sh - Robust expect wrapper for Claude Code REPL automation
# Handles readiness detection, retries, and large message injection
#
# Usage: ./worker_expect.sh <session_name> <pane_id> <message_file_or_text>
#

set timeout 15
set max_retries 5
set chunk_size 500

# Claude Code prompt patterns - adjust as needed
set prompt_patterns {
    "➜"
    "❯"
    "claude>"
    "\\\$ "
    "# "
}

proc log_msg {level message} {
    set timestamp [clock format [clock seconds] -format "%Y-%m-%d %H:%M:%S"]
    puts "\[$timestamp\] \[$level\] $message"
}

proc wait_for_prompt {max_wait} {
    global prompt_patterns
    set found 0
    
    expect {
        -re "➜|❯|claude>|\\\$ |# " { 
            set found 1 
        }
        timeout { 
            log_msg "WARN" "Timeout waiting for prompt (${max_wait}s)"
        }
    }
    return $found
}

proc send_with_retry {text max_retries} {
    set retries 0
    
    while {$retries < $max_retries} {
        log_msg "INFO" "Sending message (attempt [expr $retries + 1]/$max_retries)"
        
        # Send the text
        send -- "$text"
        
        # Send Enter
        send -- "\r"
        
        # Wait for prompt to return (indicates command was processed)
        if {[wait_for_prompt 10]} {
            log_msg "SUCCESS" "Message sent successfully"
            return 0
        }
        
        incr retries
        sleep [expr $retries * 2]  # Exponential backoff
        log_msg "WARN" "Retry $retries failed, backing off..."
    }
    
    log_msg "ERROR" "Failed to send message after $max_retries attempts"
    return 1
}

proc send_large_message {message max_retries} {
    global chunk_size
    
    set message_len [string length $message]
    log_msg "INFO" "Sending large message ($message_len chars)"
    
    if {$message_len <= $chunk_size} {
        return [send_with_retry $message $max_retries]
    }
    
    # Split into chunks
    set chunks [list]
    set pos 0
    
    while {$pos < $message_len} {
        set end [expr min($pos + $chunk_size, $message_len)]
        
        # Find a good break point (end of line)
        if {$end < $message_len} {
            set break_pos [string last "\n" [string range $message $pos $end]]
            if {$break_pos > 0} {
                set end [expr $pos + $break_pos]
            }
        }
        
        lappend chunks [string range $message $pos $end]
        set pos [expr $end + 1]
    }
    
    log_msg "INFO" "Split into [llength $chunks] chunks"
    
    # Send each chunk
    foreach chunk $chunks {
        if {[send_with_retry $chunk $max_retries] != 0} {
            return 1
        }
        sleep 1  # Brief pause between chunks
    }
    
    return 0
}

# Argument validation
if {$argc < 3} {
    puts "Usage: $argv0 <session_name> <pane_id> <message_text_or_file>"
    puts "Example: $argv0 hive-swarm 0.1 \"Hello worker!\""
    puts "Example: $argv0 hive-swarm 0.1 /path/to/message.txt"
    exit 1
}

set session_name [lindex $argv 0]
set pane_id [lindex $argv 1]
set message_input [lindex $argv 2]

log_msg "INFO" "Starting expect automation for $session_name:$pane_id"

# Check if message_input is a file or direct text
set message ""
if {[file exists $message_input]} {
    log_msg "INFO" "Reading message from file: $message_input"
    set fp [open $message_input r]
    set message [read $fp]
    close $fp
} else {
    set message $message_input
}

# Attach to the tmux pane
log_msg "INFO" "Attaching to tmux pane: $session_name:$pane_id"
spawn tmux send-keys -t "$session_name:$pane_id" ""

# Wait for the pane to be ready
log_msg "INFO" "Waiting for pane readiness..."
if {![wait_for_prompt 20]} {
    log_msg "ERROR" "Pane not ready after 20 seconds"
    exit 1
}

# Send the message
set result [send_large_message $message $max_retries]

if {$result == 0} {
    log_msg "SUCCESS" "Message delivery completed"
    exit 0
} else {
    log_msg "ERROR" "Message delivery failed"
    exit 1
}