// SPDX-License-Identifier: MIT
pragma solidity 0.8.29;

/// @notice Deliberately configurable ERC-20 test double. It can model transfer
/// pauses, address restrictions, false/no return values, transfer tax, and a
/// callback from inside transfer/transferFrom.
contract ModeToken {
    string public constant name = "Mode Token";
    string public constant symbol = "MODE";
    uint8 public constant decimals = 18;

    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;
    uint256 public totalSupply;

    bool public paused;
    bool public returnFalse;
    bool public noReturn;
    uint16 public taxBps;
    mapping(address => bool) public blockedSender;
    mapping(address => bool) public blockedRecipient;

    address public callbackTarget;
    bytes public callbackData;
    bool public callbackOnTransferFrom;
    bool public callbackOnTransfer;
    bool private inCallback;
    bool public lastCallbackSuccess;
    bytes4 public lastCallbackError;
    uint256 public callbackCount;

    event Transfer(address indexed from, address indexed to, uint256 amount);
    event Approval(address indexed owner, address indexed spender, uint256 amount);

    function mint(address to, uint256 amount) external {
        balanceOf[to] += amount;
        totalSupply += amount;
        emit Transfer(address(0), to, amount);
    }

    function approve(address spender, uint256 amount) external returns (bool) {
        allowance[msg.sender][spender] = amount;
        emit Approval(msg.sender, spender, amount);
        return true;
    }

    function configureReturns(bool false_, bool noReturn_) external {
        returnFalse = false_;
        noReturn = noReturn_;
    }

    function setPaused(bool value) external {
        paused = value;
    }

    function setTaxBps(uint16 value) external {
        require(value <= 10_000);
        taxBps = value;
    }

    function setBlockedSender(address who, bool value) external {
        blockedSender[who] = value;
    }

    function setBlockedRecipient(address who, bool value) external {
        blockedRecipient[who] = value;
    }

    function setCallback(address target, bytes calldata data, bool onTransferFrom, bool onTransfer) external {
        callbackTarget = target;
        callbackData = data;
        callbackOnTransferFrom = onTransferFrom;
        callbackOnTransfer = onTransfer;
        lastCallbackSuccess = false;
        lastCallbackError = bytes4(0);
        callbackCount = 0;
    }

    function transfer(address to, uint256 amount) external returns (bool result) {
        if (returnFalse) return false;
        _move(msg.sender, to, amount);
        if (callbackOnTransfer) _callback();
        if (noReturn) {
            assembly { return(0, 0) }
        }
        return true;
    }

    function transferFrom(address from, address to, uint256 amount) external returns (bool result) {
        if (returnFalse) return false;
        uint256 allowed = allowance[from][msg.sender];
        require(allowed >= amount, "allowance");
        if (allowed != type(uint256).max) allowance[from][msg.sender] = allowed - amount;
        _move(from, to, amount);
        if (callbackOnTransferFrom) _callback();
        if (noReturn) {
            assembly { return(0, 0) }
        }
        return true;
    }

    function _move(address from, address to, uint256 amount) private {
        require(!paused, "paused");
        require(!blockedSender[from], "sender blocked");
        require(!blockedRecipient[to], "recipient blocked");
        require(balanceOf[from] >= amount, "balance");
        balanceOf[from] -= amount;
        uint256 tax = amount * taxBps / 10_000;
        uint256 received = amount - tax;
        balanceOf[to] += received;
        totalSupply -= tax;
        emit Transfer(from, to, received);
        if (tax != 0) emit Transfer(from, address(0), tax);
    }

    function _callback() private {
        if (inCallback || callbackTarget == address(0)) return;
        inCallback = true;
        callbackCount++;
        (bool ok, bytes memory ret) = callbackTarget.call(callbackData);
        lastCallbackSuccess = ok;
        if (!ok && ret.length >= 4) {
            bytes4 selector;
            assembly { selector := mload(add(ret, 32)) }
            lastCallbackError = selector;
        }
        inCallback = false;
    }
}

/// @notice Account contract used to make the award winner itself attempt a
/// nested withdrawal when the token transfers its claim.
contract ReentrantWinner {
    address public immutable escrow;
    address public immutable recipient;
    bool public nestedSucceeded;
    bytes4 public nestedError;

    constructor(address escrow_, address recipient_) {
        escrow = escrow_;
        recipient = recipient_;
    }

    function submit(uint256 id, bytes32 hash, string calldata uri) external {
        (bool ok,) = escrow.call(abi.encodeWithSignature("submitWork(uint256,bytes32,string)", id, hash, uri));
        require(ok);
    }

    function withdraw() external {
        (bool ok,) = escrow.call(abi.encodeWithSignature("withdraw(address)", recipient));
        require(ok);
    }

    function attackWithdraw() external {
        bool ok;
        bytes memory ret;
        (ok, ret) = escrow.call(abi.encodeWithSignature("withdraw(address)", recipient));
        nestedSucceeded = ok;
        if (!nestedSucceeded && ret.length >= 4) {
            bytes4 selector;
            assembly { selector := mload(add(ret, 32)) }
            nestedError = selector;
        }
    }
}
